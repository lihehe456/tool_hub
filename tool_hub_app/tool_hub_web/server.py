#!/usr/bin/env python3

import copy
import json
import sys
import threading
import uuid
from pathlib import Path

import yaml
from flask import jsonify, request, send_from_directory

try:
    from runtime_paths import (
        default_task_editor_browse_root,
        default_user_browse_root,
        default_waypoint_attrs_root,
        default_waypoint_tasks_root,
    )
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from runtime_paths import (
        default_task_editor_browse_root,
        default_user_browse_root,
        default_waypoint_attrs_root,
        default_waypoint_tasks_root,
    )

try:
    from path_editor_web.server import create_app as create_path_editor_app
    from path_editor_web.server import pgm_to_png_base64
    from task_editor.server import register_task_editor
    from tool_hub_web.task_attribute_batch_generator import (
        generate_task_attribute_files,
        preview_task_attribute_files,
    )
    from tool_hub_web.task_batch_generator import (
        discover_template_pairs,
        generate_task_files,
        preview_task_files,
        resolve_directory,
    )
    from tool_hub_web.pcd_to_map import (
        PcdToMapOptions,
        convert_pcd_to_map,
        convert_pcd_to_map_preview,
        export_map_files,
        find_trajectory_pcd,
        project_trajectory_to_map,
        render_preview_with_trajectory,
    )
    from tool_hub_web.subtask_composer import (
        build_return_subtask,
        create_empty_subtask,
        load_task_document_file,
        load_subtask_file,
        save_task_document_file,
        save_subtask_file,
    )
    from tool_hub_web.waypoint_task_builder import (
        load_waypoint_task_file,
        save_waypoint_task_file,
        supported_waypoint_task_nodes,
    )
    from tool_hub_web.virtual_wall_builder import (
        load_virtual_wall_file,
        save_virtual_wall_file,
    )
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from path_editor_web.server import create_app as create_path_editor_app
    from path_editor_web.server import pgm_to_png_base64
    from task_editor.server import register_task_editor
    from tool_hub_web.task_attribute_batch_generator import (
        generate_task_attribute_files,
        preview_task_attribute_files,
    )
    from tool_hub_web.task_batch_generator import (
        discover_template_pairs,
        generate_task_files,
        preview_task_files,
        resolve_directory,
    )
    from tool_hub_web.pcd_to_map import (
        PcdToMapOptions,
        convert_pcd_to_map,
        convert_pcd_to_map_preview,
        export_map_files,
        find_trajectory_pcd,
        project_trajectory_to_map,
        render_preview_with_trajectory,
    )
    from tool_hub_web.subtask_composer import (
        build_return_subtask,
        create_empty_subtask,
        load_task_document_file,
        load_subtask_file,
        save_task_document_file,
        save_subtask_file,
    )
    from tool_hub_web.waypoint_task_builder import (
        load_waypoint_task_file,
        save_waypoint_task_file,
        supported_waypoint_task_nodes,
    )
    from tool_hub_web.virtual_wall_builder import (
        load_virtual_wall_file,
        save_virtual_wall_file,
    )


STATIC_DIR = Path(__file__).resolve().parent / "static"
DEFAULT_WAYPOINT_TASKS_ROOT = default_waypoint_tasks_root()
DEFAULT_TASK_EDITOR_ATTRS_ROOT = default_waypoint_attrs_root()
DEFAULT_TASK_EDITOR_BROWSE_ROOT = default_task_editor_browse_root()
DEFAULT_TASK_BATCH_GENERATOR_ROOT = default_task_editor_browse_root()
DEFAULT_TASK_ATTRIBUTE_BATCH_GENERATOR_ROOT = default_task_editor_browse_root()
DEFAULT_USER_BROWSE_ROOT = default_user_browse_root()


def create_app(config=None):
    app = create_path_editor_app(config)
    original_path_editor_index = app.view_functions["index"]
    app.config.setdefault("WAYPOINT_TASKS_ROOT", str(DEFAULT_WAYPOINT_TASKS_ROOT))
    app.config.setdefault("ATTRS_DIR", str(DEFAULT_TASK_EDITOR_ATTRS_ROOT))
    app.config.setdefault("TASK_EDITOR_DEFAULT_BROWSE_ROOT", str(DEFAULT_TASK_EDITOR_BROWSE_ROOT))
    app.config.setdefault("TASK_BATCH_GENERATOR_ROOT", str(DEFAULT_TASK_BATCH_GENERATOR_ROOT))
    app.config.setdefault(
        "TASK_ATTRIBUTE_BATCH_GENERATOR_ROOT",
        str(DEFAULT_TASK_ATTRIBUTE_BATCH_GENERATOR_ROOT),
    )
    pcd_jobs = {}
    pcd_jobs_lock = threading.Lock()

    def waypoint_tasks_root():
        return Path(app.config["WAYPOINT_TASKS_ROOT"]).expanduser().resolve()

    def json_error(message, status_code=400):
        return jsonify({"error": message}), status_code

    def create_pcd_job(kind, payload):
        job_id = uuid.uuid4().hex
        job = {
            "id": job_id,
            "kind": kind,
            "status": "queued",
            "progress": 0,
            "message": "等待处理",
            "result": None,
            "error": None,
        }
        with pcd_jobs_lock:
            pcd_jobs[job_id] = job

        thread = threading.Thread(
            target=run_pcd_job,
            args=(job_id, kind, copy.deepcopy(payload)),
            daemon=True,
        )
        thread.start()
        return job

    def update_pcd_job(job_id, **updates):
        with pcd_jobs_lock:
            if job_id in pcd_jobs:
                pcd_jobs[job_id].update(updates)

    def get_pcd_job(job_id):
        with pcd_jobs_lock:
            job = pcd_jobs.get(job_id)
            return copy.deepcopy(job) if job else None

    def run_pcd_job(job_id, kind, payload):
        try:
            update_pcd_job(job_id, status="running", progress=5, message="解析参数")
            if kind == "preview":
                result = build_pcd_preview_payload(payload, job_id)
            elif kind == "export":
                result = build_pcd_export_payload(payload, job_id)
            else:
                raise ValueError(f"Unsupported PCD job kind: {kind}")
            update_pcd_job(
                job_id,
                status="completed",
                progress=100,
                message="处理完成",
                result=result,
            )
        except (ValueError, TypeError, KeyError) as exc:
            update_pcd_job(
                job_id,
                status="failed",
                progress=100,
                message="处理失败",
                error=str(exc),
            )

    def resolve_user_path(raw_path, field_name):
        if not raw_path:
            raise ValueError(f"{field_name} is required")
        target = Path(raw_path).expanduser()
        if not target.is_absolute():
            raise ValueError(f"{field_name} must be an absolute path")
        return target.resolve()

    def browse_absolute_path(raw_path, fallback):
        raw_path = raw_path or str(fallback)
        target = Path(raw_path).expanduser()
        if not target.is_absolute():
            raise ValueError("path must be an absolute path")
        target = target.resolve()
        if not target.exists():
            target = target.parent
        if not target.is_dir():
            target = target.parent

        entries = []
        for child in sorted(target.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower())):
            entries.append(
                {
                    "name": child.name,
                    "path": str(child),
                    "is_dir": child.is_dir(),
                    "is_json": child.is_file() and child.suffix.lower() == ".json",
                    "is_yaml": child.is_file() and child.suffix.lower() in {".yaml", ".yml"},
                    "is_pgm": child.is_file() and child.suffix.lower() == ".pgm",
                    "is_pcd": child.is_file() and child.suffix.lower() == ".pcd",
                }
            )
        return {
            "cwd": str(target),
            "parent": str(target.parent),
            "entries": entries,
        }

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

    def collect_xml_stem_names(folder):
        if folder is None:
            return []
        return [
            child.stem
            for child in sorted(folder.iterdir(), key=lambda item: item.name.lower())
            if child.is_file() and child.suffix.lower() == ".xml"
        ]

    def build_pcd_preview_payload(payload, job_id=None):
        pcd_path = resolve_user_path(payload.get("pcd_path", ""), "pcd_path")
        slices = payload.get("slices") or []
        if not slices:
            raise ValueError("slices is required")

        trajectory_path = find_trajectory_pcd(pcd_path)
        trajectory_result = None
        previews = []
        total = max(len(slices), 1)
        for index, slice_payload in enumerate(slices):
            update_pcd_job(
                job_id,
                progress=10 + int(index * 80 / total),
                message=f"生成切片 {index + 1}/{total}",
            ) if job_id else None
            result = convert_pcd_to_map_preview(
                pcd_path,
                pcd_options_from_payload(payload, slice_payload),
                fast_preview=bool(payload.get("fast_preview")),
            )
            preview_dict = result.to_preview_dict(slice_payload.get("id", f"slice-{index + 1}"))
            if trajectory_path and payload.get("include_trajectory_preview"):
                trajectory_result = project_trajectory_to_map(
                    trajectory_path,
                    result,
                    payload.get("odom_to_lidar_odom"),
                )
                preview_dict["preview_png_base64"] = render_preview_with_trajectory(
                    result,
                    trajectory_result,
                )
                preview_dict["trajectory"] = trajectory_result.to_preview_dict()
            previews.append(preview_dict)

        response_payload = {"slices": previews}
        if trajectory_path and payload.get("include_trajectory_preview"):
            response_payload["trajectory"] = (
                trajectory_result.to_preview_dict() if trajectory_result else None
            )
        return response_payload

    def build_pcd_export_payload(payload, job_id=None):
        update_pcd_job(job_id, progress=10, message="生成完整地图") if job_id else None
        pcd_path = resolve_user_path(payload.get("pcd_path", ""), "pcd_path")
        output_dir = resolve_user_path(payload.get("output_dir", ""), "output_dir")
        slice_payload = payload.get("slice") or {}
        result = convert_pcd_to_map(pcd_path, pcd_options_from_payload(payload, slice_payload))
        trajectory_path = find_trajectory_pcd(pcd_path)
        trajectory_mask = None
        if trajectory_path and (
            payload.get("include_trajectory_export")
            or payload.get("include_trajectory_overlay")
        ):
            update_pcd_job(job_id, progress=75, message="投影轨迹蒙版") if job_id else None
            trajectory_mask = project_trajectory_to_map(
                trajectory_path,
                result,
                payload.get("odom_to_lidar_odom"),
            )
        update_pcd_job(job_id, progress=88, message="写出地图文件") if job_id else None
        exported = export_map_files(
            result,
            output_dir,
            payload.get("map_name", "map"),
            trajectory_mask=trajectory_mask,
            include_trajectory_overlay=bool(payload.get("include_trajectory_overlay")),
        )
        response_payload = {"ok": True, **exported, "map": result.to_preview_dict()}
        if trajectory_mask is not None:
            response_payload["trajectory"] = trajectory_mask.to_preview_dict()
        return response_payload

    def parse_optional_int(value):
        if value in (None, ""):
            return None
        return int(value)

    def pcd_options_from_payload(payload, slice_payload):
        transform = payload.get("odom_to_lidar_odom") or [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        return PcdToMapOptions(
            z_min=float(slice_payload.get("z_min")),
            z_max=float(slice_payload.get("z_max")),
            resolution=float(payload.get("resolution", 0.05)),
            radius=float(payload.get("radius", 0.5)),
            min_neighbors=int(payload.get("min_neighbors", 10)),
            flag_pass_through=bool(payload.get("flag_pass_through", False)),
            odom_to_lidar_odom=tuple(float(value) for value in transform),
        )

    @app.get("/hub-static/<path:filename>")
    def hub_static(filename):
        return send_from_directory(STATIC_DIR, filename)

    @app.get("/path-editor")
    def path_editor_page():
        return original_path_editor_index()

    @app.get("/")
    def hub_index():
        return send_from_directory(STATIC_DIR, "index.html")

    @app.get("/waypoint-task-builder")
    def waypoint_task_builder_page():
        return send_from_directory(STATIC_DIR, "waypoint-task-builder.html")

    @app.get("/task-batch-generator")
    def task_batch_generator_page():
        return send_from_directory(STATIC_DIR, "task-batch-generator.html")

    @app.get("/task-attribute-batch-generator")
    def task_attribute_batch_generator_page():
        return send_from_directory(STATIC_DIR, "task-attribute-batch-generator.html")

    @app.get("/virtual-wall-builder")
    def virtual_wall_builder_page():
        return send_from_directory(STATIC_DIR, "virtual-wall-builder.html")

    @app.get("/pcd-to-map")
    def pcd_to_map_page():
        return send_from_directory(STATIC_DIR, "pcd-to-map.html")

    @app.get("/subtask-composer")
    def subtask_composer_page():
        return send_from_directory(STATIC_DIR, "subtask-composer.html")

    @app.get("/waypoint-task-builder/api/runtime_config")
    def waypoint_task_builder_runtime_config():
        return jsonify({"waypoint_tasks_root": str(waypoint_tasks_root())})

    @app.get("/task-batch-generator/api/runtime_config")
    def task_batch_generator_runtime_config():
        return jsonify(
            {
                "default_root": str(Path(app.config["TASK_BATCH_GENERATOR_ROOT"]).expanduser().resolve()),
            }
        )

    @app.get("/task-attribute-batch-generator/api/runtime_config")
    def task_attribute_batch_generator_runtime_config():
        return jsonify(
            {
                "default_root": str(
                    Path(app.config["TASK_ATTRIBUTE_BATCH_GENERATOR_ROOT"]).expanduser().resolve()
                ),
            }
        )

    @app.get("/virtual-wall-builder/api/runtime_config")
    def virtual_wall_builder_runtime_config():
        return jsonify(
            {
                "default_root": str(DEFAULT_USER_BROWSE_ROOT),
                "default_frame_id": "map",
                "default_thickness": 0.1,
            }
        )

    @app.get("/pcd-to-map/api/runtime_config")
    def pcd_to_map_runtime_config():
        return jsonify({"default_root": str(DEFAULT_USER_BROWSE_ROOT)})

    @app.get("/subtask-composer/api/runtime_config")
    def subtask_composer_runtime_config():
        attrs_dir = Path(app.config["ATTRS_DIR"])
        return jsonify(
            {
                "default_root": str(DEFAULT_USER_BROWSE_ROOT),
                "default_waypoint_tasks_path": str(attrs_dir / "waypoint_tasks"),
                "default_speed_modes_path": str(attrs_dir / "speed_modes"),
            }
        )

    @app.get("/subtask-composer/api/attributes")
    def subtask_composer_attributes():
        attrs_dir = Path(app.config["ATTRS_DIR"])
        try:
            speed_dir = resolve_attribute_dir(
                request.args.get("speed_modes_path", ""),
                "speed_modes_path",
                attrs_dir / "speed_modes",
            )
            task_dir = resolve_attribute_dir(
                request.args.get("waypoint_tasks_path", ""),
                "waypoint_tasks_path",
                attrs_dir / "waypoint_tasks",
            )
        except ValueError as exc:
            return json_error(str(exc), 400)

        speed_single_dir = speed_dir / "single_point" if speed_dir is not None else None
        return jsonify(
            {
                "speed_modes": collect_xml_stem_names(speed_dir),
                "speed_modes_single": collect_xml_stem_names(speed_single_dir)
                if speed_single_dir is not None and speed_single_dir.is_dir()
                else [],
                "waypoint_tasks": collect_xml_stem_names(task_dir),
            }
        )

    @app.post("/subtask-composer/api/browse")
    def subtask_composer_browse():
        raw_path = (request.get_json(silent=True) or {}).get("path", str(DEFAULT_USER_BROWSE_ROOT))
        try:
            return jsonify(browse_absolute_path(raw_path, DEFAULT_USER_BROWSE_ROOT))
        except ValueError as exc:
            return json_error(str(exc), 400)

    @app.post("/subtask-composer/api/load")
    def subtask_composer_load():
        payload = request.get_json(silent=True) or {}
        try:
            target = resolve_user_path(payload.get("path", ""), "path")
            if not target.is_file():
                return json_error(f"Subtask file not found: {target}", 404)
            document_payload = load_task_document_file(target)
            active_index = document_payload["active_subtask_index"]
            active_subtask = (
                document_payload["subtasks"][active_index]
                if active_index >= 0
                else create_empty_subtask("new_subtask")
            )
            return jsonify(
                {
                    "path": str(target),
                    "subtask": active_subtask,
                    **document_payload,
                }
            )
        except (ValueError, json.JSONDecodeError) as exc:
            return json_error(str(exc), 400)

    @app.post("/subtask-composer/api/new")
    def subtask_composer_new():
        payload = request.get_json(silent=True) or {}
        subtask_name = (payload.get("subtask_name") or "new_subtask").strip()
        return jsonify(
            {
                "subtask": create_empty_subtask(
                    subtask_name=subtask_name,
                    map_url=payload.get("map_url", ""),
                    pcd_url=payload.get("pcd_url", ""),
                    change_loc=payload.get("change_loc", False),
                )
            }
        )

    @app.post("/subtask-composer/api/save")
    def subtask_composer_save():
        payload = request.get_json(silent=True) or {}
        try:
            target = resolve_user_path(payload.get("path", ""), "path")
            if "subtasks" in payload or "task_group" in payload:
                saved_path = save_task_document_file(target, payload)
                document_payload = load_task_document_file(saved_path)
                active_index = document_payload["active_subtask_index"]
                active_subtask = (
                    document_payload["subtasks"][active_index]
                    if active_index >= 0
                    else create_empty_subtask("new_subtask")
                )
                return jsonify(
                    {
                        "ok": True,
                        "path": str(saved_path),
                        "subtask": active_subtask,
                        **document_payload,
                    }
                )

            subtask = payload.get("subtask")
            if subtask is None:
                return json_error("subtask is required", 400)
            saved_path = save_subtask_file(target, subtask)
            document_payload = load_task_document_file(saved_path)
            return jsonify(
                {
                    "ok": True,
                    "path": str(saved_path),
                    "subtask": document_payload["subtasks"][0],
                    **document_payload,
                }
            )
        except ValueError as exc:
            return json_error(str(exc), 400)

    @app.post("/subtask-composer/api/build_return")
    def subtask_composer_build_return():
        payload = request.get_json(silent=True) or {}
        try:
            subtask = payload.get("subtask")
            if subtask is None:
                return json_error("subtask is required", 400)
            return_subtask = build_return_subtask(
                subtask,
                subtask_name=payload.get("subtask_name") or None,
                waypoint_prefix=payload.get("waypoint_prefix") or None,
            )
            output_path = payload.get("output_path", "")
            response_payload = {"subtask": return_subtask}
            if output_path:
                target = resolve_user_path(output_path, "output_path")
                saved_path = save_subtask_file(target, return_subtask)
                response_payload.update({"ok": True, "path": str(saved_path)})
            return jsonify(response_payload)
        except ValueError as exc:
            return json_error(str(exc), 400)

    @app.post("/pcd-to-map/api/browse")
    def pcd_to_map_browse():
        raw_path = (request.get_json(silent=True) or {}).get("path", str(DEFAULT_USER_BROWSE_ROOT))
        try:
            return jsonify(browse_absolute_path(raw_path, DEFAULT_USER_BROWSE_ROOT))
        except ValueError as exc:
            return json_error(str(exc), 400)

    @app.post("/pcd-to-map/api/preview")
    def pcd_to_map_preview():
        payload = request.get_json(silent=True) or {}
        try:
            response_payload = build_pcd_preview_payload(payload)
        except (ValueError, TypeError, KeyError) as exc:
            return json_error(str(exc), 400)
        return jsonify(response_payload)

    @app.post("/pcd-to-map/api/preview_job")
    def pcd_to_map_preview_job():
        job = create_pcd_job("preview", request.get_json(silent=True) or {})
        return jsonify({"job_id": job["id"], "status": job["status"], "progress": job["progress"]}), 202

    @app.get("/pcd-to-map/api/preview_job/<job_id>")
    def pcd_to_map_preview_job_status(job_id):
        job = get_pcd_job(job_id)
        if not job:
            return json_error("job not found", 404)
        return jsonify(job)

    @app.post("/pcd-to-map/api/export")
    def pcd_to_map_export():
        payload = request.get_json(silent=True) or {}
        try:
            response_payload = build_pcd_export_payload(payload)
        except (ValueError, TypeError, KeyError) as exc:
            return json_error(str(exc), 400)
        return jsonify(response_payload)

    @app.post("/pcd-to-map/api/export_job")
    def pcd_to_map_export_job():
        job = create_pcd_job("export", request.get_json(silent=True) or {})
        return jsonify({"job_id": job["id"], "status": job["status"], "progress": job["progress"]}), 202

    @app.get("/pcd-to-map/api/export_job/<job_id>")
    def pcd_to_map_export_job_status(job_id):
        job = get_pcd_job(job_id)
        if not job:
            return json_error("job not found", 404)
        return jsonify(job)

    @app.post("/virtual-wall-builder/api/browse")
    def virtual_wall_builder_browse():
        raw_path = (request.get_json(silent=True) or {}).get("path", str(DEFAULT_USER_BROWSE_ROOT))
        try:
            return jsonify(browse_absolute_path(raw_path, DEFAULT_USER_BROWSE_ROOT))
        except ValueError as exc:
            return json_error(str(exc), 400)

    @app.post("/virtual-wall-builder/api/save")
    def virtual_wall_builder_save():
        payload = request.get_json(silent=True) or {}
        try:
            target = resolve_user_path(payload.get("path", ""), "path")
            saved_path = save_virtual_wall_file(
                target,
                polylines=payload.get("polylines", []),
                map_origin=payload.get("map_origin", []),
                frame_id=payload.get("frame_id", "map"),
                default_thickness=float(payload.get("thickness", 0.1)),
            )
        except (ValueError, TypeError) as exc:
            return json_error(str(exc), 400)
        return jsonify({"ok": True, "path": str(saved_path)})

    @app.post("/virtual-wall-builder/api/load")
    def virtual_wall_builder_load():
        payload = request.get_json(silent=True) or {}
        try:
            target = resolve_user_path(payload.get("path", ""), "path")
            document = load_virtual_wall_file(
                target,
                current_map_origin=payload.get("current_map_origin"),
            )
        except ValueError as exc:
            return json_error(str(exc), 400)
        return jsonify({"document": document, "path": str(target)})

    @app.post("/virtual-wall-builder/api/load_map")
    def virtual_wall_builder_load_map():
        payload = request.get_json(silent=True) or {}
        try:
            yaml_path = resolve_user_path(payload.get("yaml_path", ""), "yaml_path")
        except ValueError as exc:
            return json_error(str(exc), 400)
        if not yaml_path.is_file():
            return json_error(f"Map yaml not found: {yaml_path}", 404)

        try:
            meta = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
            image_name = meta.get("image")
            if not image_name:
                return json_error(f"Map yaml missing image field: {yaml_path}", 400)
            pgm_path = (yaml_path.parent / image_name).resolve()
            if not pgm_path.is_file():
                return json_error(f"PGM not found: {pgm_path}", 404)
            image_b64, width, height = pgm_to_png_base64(pgm_path)
        except (OSError, ValueError, yaml.YAMLError) as exc:
            return json_error(str(exc), 400)

        return jsonify(
            {
                "image_b64": image_b64,
                "resolution": meta.get("resolution"),
                "origin": meta.get("origin"),
                "width": width,
                "height": height,
                "yaml_path": str(yaml_path),
                "image_path": str(pgm_path),
            }
        )

    @app.get("/waypoint-task-builder/api/schema")
    def waypoint_task_builder_schema():
        return jsonify({"nodes": supported_waypoint_task_nodes()})

    @app.post("/waypoint-task-builder/api/browse")
    def waypoint_task_builder_browse():
        raw_path = (request.get_json(silent=True) or {}).get("path", str(waypoint_tasks_root()))
        try:
            target = resolve_user_path(raw_path, "path")
        except ValueError as exc:
            return json_error(str(exc), 400)
        if not target.exists():
            target = target.parent
        if not target.is_dir():
            target = target.parent

        entries = []
        for child in sorted(target.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower())):
            entries.append(
                {
                    "name": child.name,
                    "path": str(child),
                    "is_dir": child.is_dir(),
                    "is_xml": child.is_file() and child.suffix.lower() == ".xml",
                }
            )

        return jsonify(
            {
                "cwd": str(target),
                "parent": str(target.parent),
                "entries": entries,
            }
        )

    @app.post("/waypoint-task-builder/api/load")
    def waypoint_task_builder_load():
        raw_path = (request.get_json(silent=True) or {}).get("path", "")
        try:
            task_path = resolve_user_path(raw_path, "path")
        except ValueError as exc:
            return json_error(str(exc), 400)
        if not task_path.is_file():
            return json_error(f"Task file not found: {task_path}", 404)
        try:
            document = load_waypoint_task_file(task_path)
        except ValueError as exc:
            return json_error(str(exc), 400)
        return jsonify({"document": document, "path": str(task_path), "xml_text": task_path.read_text(encoding="utf-8")})

    @app.post("/waypoint-task-builder/api/parse_xml")
    def waypoint_task_builder_parse_xml():
        payload = request.get_json(silent=True) or {}
        task_name = payload.get("task_name", "").strip() or "parsed_task"
        xml_text = payload.get("xml_text", "")
        if not xml_text:
            return json_error("xml_text is required", 400)
        try:
            from tool_hub_web.waypoint_task_builder import parse_waypoint_task_xml
            document = parse_waypoint_task_xml(xml_text, task_name=task_name)
        except ValueError as exc:
            return json_error(str(exc), 400)
        return jsonify({"document": document, "xml_text": xml_text})

    @app.post("/waypoint-task-builder/api/save")
    def waypoint_task_builder_save():
        payload = request.get_json(silent=True) or {}
        raw_directory = payload.get("directory", "")
        task_name = payload.get("task_name", "").strip()
        document = payload.get("document")
        try:
            directory = resolve_user_path(raw_directory, "directory")
        except ValueError as exc:
            return json_error(str(exc), 400)
        if not task_name:
            return json_error("task_name is required", 400)
        if document is None:
            return json_error("document is required", 400)
        try:
            task_path = save_waypoint_task_file(directory, task_name, document)
        except ValueError as exc:
            return json_error(str(exc), 400)
        return jsonify({"ok": True, "path": str(task_path)})

    @app.post("/task-batch-generator/api/browse")
    def task_batch_generator_browse():
        raw_path = (request.get_json(silent=True) or {}).get(
            "path",
            str(Path(app.config["TASK_BATCH_GENERATOR_ROOT"]).expanduser().resolve()),
        )
        try:
            target = resolve_directory(raw_path)
        except ValueError as exc:
            return json_error(str(exc), 400)
        if not target.exists():
            target = target.parent
        if not target.is_dir():
            target = target.parent

        entries = []
        for child in sorted(target.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower())):
            entries.append(
                {
                    "name": child.name,
                    "path": str(child),
                    "is_dir": child.is_dir(),
                    "is_json": child.is_file() and child.suffix.lower() == ".json",
                }
            )

        return jsonify(
            {
                "cwd": str(target),
                "parent": str(target.parent),
                "entries": entries,
            }
        )

    @app.post("/task-attribute-batch-generator/api/browse")
    def task_attribute_batch_generator_browse():
        raw_path = (request.get_json(silent=True) or {}).get(
            "path",
            str(Path(app.config["TASK_ATTRIBUTE_BATCH_GENERATOR_ROOT"]).expanduser().resolve()),
        )
        try:
            target = resolve_directory(raw_path)
        except ValueError as exc:
            return json_error(str(exc), 400)
        if not target.exists():
            target = target.parent
        if not target.is_dir():
            target = target.parent

        entries = []
        for child in sorted(target.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower())):
            entries.append(
                {
                    "name": child.name,
                    "path": str(child),
                    "is_dir": child.is_dir(),
                    "is_json": child.is_file() and child.suffix.lower() == ".json",
                    "is_xml": child.is_file() and child.suffix.lower() == ".xml",
                }
            )

        return jsonify(
            {
                "cwd": str(target),
                "parent": str(target.parent),
                "entries": entries,
            }
        )

    @app.post("/task-batch-generator/api/scan")
    def task_batch_generator_scan():
        payload = request.get_json(silent=True) or {}
        raw_directory = payload.get("directory", "")
        try:
            directory = resolve_directory(raw_directory)
        except ValueError as exc:
            return json_error(str(exc), 400)
        if not directory.exists() or not directory.is_dir():
            return json_error(f"Directory not found: {directory}", 404)
        return jsonify({"pairs": discover_template_pairs(directory)})

    @app.post("/task-batch-generator/api/preview")
    def task_batch_generator_preview():
        payload = request.get_json(silent=True) or {}
        try:
            preview = preview_task_files(
                template_01=payload.get("template_01", ""),
                template_03=payload.get("template_03", ""),
                start=int(payload.get("start", 0)),
                end=int(payload.get("end", 0)),
                output_dir=payload.get("output_dir", ""),
                elevator_floor=parse_optional_int(payload.get("elevator_floor")),
            )
        except (ValueError, TypeError) as exc:
            return json_error(str(exc), 400)
        return jsonify(preview)

    @app.post("/task-batch-generator/api/generate")
    def task_batch_generator_generate():
        payload = request.get_json(silent=True) or {}
        try:
            result = generate_task_files(
                template_01=payload.get("template_01", ""),
                template_03=payload.get("template_03", ""),
                start=int(payload.get("start", 0)),
                end=int(payload.get("end", 0)),
                output_dir=payload.get("output_dir", ""),
                overwrite=bool(payload.get("overwrite", False)),
                elevator_floor=parse_optional_int(payload.get("elevator_floor")),
            )
        except (ValueError, TypeError, FileExistsError) as exc:
            return json_error(str(exc), 400)
        return jsonify(result)

    @app.post("/task-attribute-batch-generator/api/preview")
    def task_attribute_batch_generator_preview():
        payload = request.get_json(silent=True) or {}
        try:
            preview = preview_task_attribute_files(
                reference_task_path=payload.get("reference_task_path", ""),
                template_xml_path=payload.get("template_xml_path", ""),
                start=int(payload.get("start", 0)),
                end=int(payload.get("end", 0)),
                output_dir=payload.get("output_dir", ""),
            )
        except (ValueError, TypeError) as exc:
            return json_error(str(exc), 400)
        return jsonify(preview)

    @app.post("/task-attribute-batch-generator/api/generate")
    def task_attribute_batch_generator_generate():
        payload = request.get_json(silent=True) or {}
        try:
            result = generate_task_attribute_files(
                reference_task_path=payload.get("reference_task_path", ""),
                template_xml_path=payload.get("template_xml_path", ""),
                start=int(payload.get("start", 0)),
                end=int(payload.get("end", 0)),
                output_dir=payload.get("output_dir", ""),
                overwrite=bool(payload.get("overwrite", False)),
            )
        except (ValueError, TypeError, FileExistsError) as exc:
            return json_error(str(exc), 400)
        return jsonify(result)

    app.view_functions["index"] = hub_index
    register_task_editor(app, url_prefix="/task-editor")
    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=7791, debug=False)
