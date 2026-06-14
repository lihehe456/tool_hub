#!/usr/bin/env python3

import argparse
import sys
import webbrowser
from pathlib import Path

try:
    from runtime_paths import (
        default_maps_root,
        default_paths_root,
        default_task_editor_browse_root,
        default_waypoint_attrs_root,
        default_waypoint_tasks_root,
    )
    from tool_hub_web.server import create_app
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from runtime_paths import (
        default_maps_root,
        default_paths_root,
        default_task_editor_browse_root,
        default_waypoint_attrs_root,
        default_waypoint_tasks_root,
    )
    from tool_hub_web.server import create_app


def resolve_optional_path(raw_path):
    if not raw_path:
        return None
    return str(Path(raw_path).expanduser().resolve())


def build_runtime_config(args):
    return {
        "PATHS_ROOT": resolve_optional_path(args.paths_root) or str(default_paths_root()),
        "MAPS_ROOT": resolve_optional_path(args.maps_root) or str(default_maps_root()),
        "WAYPOINT_TASKS_ROOT": resolve_optional_path(args.waypoint_tasks_root)
        or str(default_waypoint_tasks_root()),
        "ATTRS_DIR": resolve_optional_path(args.attrs_dir) or str(default_waypoint_attrs_root()),
        "TASK_EDITOR_DEFAULT_BROWSE_ROOT": resolve_optional_path(args.tasks_root)
        or str(default_task_editor_browse_root()),
    }


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Run RY-Robot Tool Hub Web")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=7791)
    parser.add_argument("--open-browser", action="store_true")
    parser.add_argument("--paths-root", help="Default browse root for path JSON files")
    parser.add_argument("--maps-root", help="Default browse root for map YAML files")
    parser.add_argument("--tasks-root", help="Default browse root for task-group JSON files")
    parser.add_argument("--waypoint-tasks-root", help="Default browse root for waypoint task XML files")
    parser.add_argument("--attrs-dir", help="Directory containing waypoints_attributes resources")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    app = create_app(build_runtime_config(args))
    if args.open_browser:
        webbrowser.open(f"http://{args.host}:{args.port}/")
    app.run(host=args.host, port=args.port, debug=False)


if __name__ == "__main__":
    main()
