#!/usr/bin/env python3
# Author: Ming Yu Li & Alex
# Email: 1323653732@qq.com

import base64
import json
from json import JSONDecodeError
import os
import struct
import sys
import zlib
from pathlib import Path

import yaml
from flask import Blueprint, Flask, jsonify, request, send_from_directory

try:
    from runtime_paths import default_task_editor_browse_root, default_waypoint_attrs_root
except ModuleNotFoundError:
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from runtime_paths import default_task_editor_browse_root, default_waypoint_attrs_root

ATTRS_DIR = os.path.realpath(str(default_waypoint_attrs_root()))
TASK_EDITOR_STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")

try:
    from path_editor_web.task_group_builder import (
        build_workspace_from_task_group_document,
        load_workspace_file,
        save_workspace_file,
        sidecar_path_for_task_group_path,
        sync_workspace_with_task_group_document,
    )
except ImportError:
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from path_editor_web.task_group_builder import (
        build_workspace_from_task_group_document,
        load_workspace_file,
        save_workspace_file,
        sidecar_path_for_task_group_path,
        sync_workspace_with_task_group_document,
    )


def pgm_to_png_base64(pgm_path):
    with open(pgm_path, "rb") as file_obj:
        magic = file_obj.readline().strip()
        assert magic == b"P5", f"Only binary PGM (P5) supported, got {magic}"
        line = file_obj.readline()
        while line.startswith(b"#"):
            line = file_obj.readline()
        width, height = map(int, line.split())
        file_obj.readline().strip()
        raw = file_obj.read()

    def make_chunk(chunk_type, data):
        chunk = chunk_type + data
        return struct.pack(">I", len(data)) + chunk + struct.pack(">I", zlib.crc32(chunk) & 0xFFFFFFFF)

    png = b"\x89PNG\r\n\x1a\n"
    png += make_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0))

    raw_rows = []
    for y_pos in range(height):
        row = raw[y_pos * width:(y_pos + 1) * width]
        raw_rows.append(b"\x00" + row)
    png += make_chunk(b"IDAT", zlib.compress(b"".join(raw_rows)))
    png += make_chunk(b"IEND", b"")

    return base64.b64encode(png).decode()


def register_task_editor(app, url_prefix=""):
    normalized_prefix = (url_prefix or "").rstrip("/")
    if normalized_prefix == "/":
        normalized_prefix = ""
    page_route = normalized_prefix or "/"
    api_prefix = f"{normalized_prefix}/api" if normalized_prefix else "/api"
    static_prefix = f"{normalized_prefix}/static" if normalized_prefix else "/static"
    blueprint = Blueprint(
        "task_editor",
        __name__,
        url_prefix="",
    )

    def json_error(message, status_code=400):
        return jsonify({"error": message}), status_code

    def resolve_attribute_dir(raw_path, field_name, default_path):
        used_default = not raw_path
        candidate = Path(raw_path).expanduser() if raw_path else Path(default_path)
        if not candidate.is_absolute():
            raise ValueError(f"{field_name} must be an absolute path")
        target = candidate.resolve()
        if not target.is_dir():
            if used_default:
                return None
            raise ValueError(f"{field_name} directory not found: {target}")
        return target

    def load_task_document(path):
        if not os.path.isfile(path):
            return None, json_error(f"File not found: {path}", 404)
        with open(path, encoding="utf-8") as file_obj:
            return json.load(file_obj), None

    def save_task_document(path, task):
        with open(path, "w", encoding="utf-8") as file_obj:
            json.dump(task, file_obj, ensure_ascii=False, indent=4)

    def try_load_workspace_file(path):
        try:
            return load_workspace_file(path), None
        except (OSError, JSONDecodeError) as exc:
            return None, str(exc)

    @blueprint.route(page_route)
    def index():
        with open(os.path.join(TASK_EDITOR_STATIC_DIR, "index.html"), encoding="utf-8") as file_obj:
            html = file_obj.read()
        if normalized_prefix:
            html = html.replace('fetch("/api/', f'fetch("{api_prefix}/')
            html = html.replace("fetch('/api/", f"fetch('{api_prefix}/")
        return html

    @blueprint.route(f"{api_prefix}/runtime_config", methods=["GET"])
    def runtime_config():
        attrs_dir = app.config["ATTRS_DIR"]
        default_browse_root = app.config.get("TASK_EDITOR_DEFAULT_BROWSE_ROOT")
        if not default_browse_root:
            default_browse_root = str(default_task_editor_browse_root())
        default_waypoint_tasks_path = str(Path(attrs_dir) / "waypoint_tasks")
        default_speed_modes_path = str(Path(attrs_dir) / "speed_modes")
        return jsonify(
            {
                "attrs_dir": attrs_dir,
                "default_browse_root": default_browse_root,
                "default_waypoint_tasks_path": default_waypoint_tasks_path,
                "default_speed_modes_path": default_speed_modes_path,
            }
        )

    @blueprint.route(f"{api_prefix}/load_task", methods=["POST"])
    def load_task():
        path = request.json.get("path", "")
        task, error = load_task_document(path)
        if error:
            return error
        return jsonify(task)

    @blueprint.route(f"{api_prefix}/load_task_bundle", methods=["POST"])
    def load_task_bundle():
        path = request.json.get("path", "")
        task, error = load_task_document(path)
        if error:
            return error

        sidecar_path = sidecar_path_for_task_group_path(path)
        sidecar_exists = sidecar_path.is_file()
        workspace = None
        sidecar_error = ""
        if sidecar_exists:
            workspace, sidecar_error = try_load_workspace_file(sidecar_path)
            if sidecar_error:
                sidecar_exists = False
        return jsonify(
            {
                "task": task,
                "sidecar_exists": sidecar_exists,
                "sidecar_path": str(sidecar_path),
                "workspace": workspace,
                "sidecar_error": sidecar_error,
            }
        )

    @blueprint.route(f"{api_prefix}/build_task_workspace_sidecar", methods=["POST"])
    def build_task_workspace_sidecar():
        path = request.json.get("path", "")
        task, error = load_task_document(path)
        if error:
            return error

        sidecar_path = sidecar_path_for_task_group_path(path)
        workspace = build_workspace_from_task_group_document(task, path)
        workspace = save_workspace_file(sidecar_path, workspace)
        return jsonify(
            {
                "workspace": workspace,
                "sidecar_path": str(sidecar_path),
            }
        )

    @blueprint.route(f"{api_prefix}/load_map", methods=["POST"])
    def load_map():
        yaml_path = request.json.get("yaml_path", "")
        if not yaml_path or not os.path.isfile(yaml_path):
            return json_error("map_url empty or not found", 404)

        with open(yaml_path, encoding="utf-8") as file_obj:
            meta = yaml.safe_load(file_obj)

        pgm_path = os.path.join(os.path.dirname(yaml_path), meta["image"])
        if not os.path.isfile(pgm_path):
            return json_error(f"PGM not found: {pgm_path}", 404)

        img_b64 = pgm_to_png_base64(pgm_path)
        return jsonify(
            {
                "image_b64": img_b64,
                "resolution": meta["resolution"],
                "origin": meta["origin"],
            }
        )

    @blueprint.route(f"{api_prefix}/attributes", methods=["GET"])
    def get_attributes():
        def collect_names(folder):
            names = []
            for file_name in sorted(os.listdir(folder)):
                full_path = os.path.join(folder, file_name)
                if os.path.isfile(full_path) and file_name.endswith(".xml"):
                    names.append(os.path.splitext(file_name)[0])
            return names

        attrs_dir = app.config["ATTRS_DIR"]
        try:
            speed_dir = resolve_attribute_dir(
                request.args.get("speed_modes_path", ""),
                "speed_modes_path",
                Path(attrs_dir) / "speed_modes",
            )
            task_dir = resolve_attribute_dir(
                request.args.get("waypoint_tasks_path", ""),
                "waypoint_tasks_path",
                Path(attrs_dir) / "waypoint_tasks",
            )
        except ValueError as exc:
            return json_error(str(exc), 400)

        if speed_dir is None or task_dir is None:
            return jsonify(
                {
                    "speed_modes": collect_names(str(speed_dir)) if speed_dir is not None else [],
                    "speed_modes_single": collect_names(str(speed_dir / "single_point"))
                    if speed_dir is not None and (speed_dir / "single_point").is_dir()
                    else [],
                    "waypoint_tasks": collect_names(str(task_dir)) if task_dir is not None else [],
                }
            )

        speed_single_dir = speed_dir / "single_point"
        speed_modes_single = collect_names(str(speed_single_dir)) if speed_single_dir.is_dir() else []
        return jsonify(
            {
                "speed_modes": collect_names(str(speed_dir)),
                "speed_modes_single": speed_modes_single,
                "waypoint_tasks": collect_names(str(task_dir)),
            }
        )

    @blueprint.route(f"{api_prefix}/browse", methods=["POST"])
    def browse():
        default_browse_root = app.config.get("TASK_EDITOR_DEFAULT_BROWSE_ROOT") or str(default_task_editor_browse_root())
        path = request.json.get("path", default_browse_root)
        if not os.path.isdir(path):
            path = os.path.dirname(path)
        entries = []
        try:
            for name in sorted(os.listdir(path)):
                full_path = os.path.join(path, name)
                entries.append(
                    {
                        "name": name,
                        "path": full_path,
                        "is_dir": os.path.isdir(full_path),
                        "is_json": name.endswith(".json"),
                    }
                )
        except PermissionError:
            pass
        return jsonify({"cwd": path, "parent": os.path.dirname(path), "entries": entries})

    @blueprint.route(f"{api_prefix}/save_task", methods=["POST"])
    def save_task():
        data = request.json
        path = data.get("path", "")
        task = data.get("task", {})
        if not path:
            return json_error("No path provided")
        save_task_document(path, task)
        return jsonify({"ok": True})

    @blueprint.route(f"{api_prefix}/save_task_bundle", methods=["POST"])
    def save_task_bundle():
        data = request.json
        path = data.get("path", "")
        task = data.get("task", {})
        if not path:
            return json_error("No path provided")

        save_task_document(path, task)
        sidecar_path = sidecar_path_for_task_group_path(path)
        if sidecar_path.is_file():
            existing_workspace, sidecar_error = try_load_workspace_file(sidecar_path)
            if existing_workspace is not None:
                workspace = sync_workspace_with_task_group_document(existing_workspace, task, path)
            else:
                workspace = build_workspace_from_task_group_document(task, path)
        else:
            sidecar_error = ""
            workspace = build_workspace_from_task_group_document(task, path)
        workspace = save_workspace_file(sidecar_path, workspace)
        return jsonify(
            {
                "ok": True,
                "sidecar_path": str(sidecar_path),
                "workspace": workspace,
                "sidecar_error": sidecar_error,
            }
        )

    @blueprint.route(f"{static_prefix}/<path:filename>")
    def static_files(filename):
        return send_from_directory(TASK_EDITOR_STATIC_DIR, filename)

    app.register_blueprint(blueprint)
    return app


def create_app(config=None, url_prefix=""):
    app = Flask(__name__, static_folder="static")
    app.config.from_mapping(
        ATTRS_DIR=ATTRS_DIR,
        TASK_EDITOR_DEFAULT_BROWSE_ROOT=str(default_task_editor_browse_root()),
    )
    if config:
        if "TASK_EDITOR_DEFAULT_BROWSE_ROOT" not in config and "ATTRS_DIR" in config:
            config = {
                **config,
                "TASK_EDITOR_DEFAULT_BROWSE_ROOT": str(Path(config["ATTRS_DIR"]).resolve().parent),
            }
        app.config.update(config)
    register_task_editor(app, url_prefix=url_prefix)
    return app


app = create_app()


if __name__ == "__main__":
    app.run(port=7788, debug=False)
