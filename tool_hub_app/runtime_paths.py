from pathlib import Path
import sys

DEFAULT_WORK_ROOT = Path("/opt/ry")


def source_repo_root():
    return Path(__file__).resolve().parent


def app_base_dir():
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", "")
        if meipass:
            return Path(meipass).resolve()
        executable_dir = Path(sys.executable).resolve().parent
        internal_dir = executable_dir / "_internal"
        if internal_dir.exists():
            return internal_dir
        return executable_dir
    return source_repo_root()


def packaged_data_dir(*parts):
    return app_base_dir().joinpath(*parts)


def source_data_dir(*parts):
    return source_repo_root().joinpath(*parts)


def packaged_or_source_path(*parts):
    packaged_candidate = packaged_data_dir(*parts)
    if packaged_candidate.exists():
        return packaged_candidate
    return source_data_dir(*parts)


def default_user_browse_root():
    return DEFAULT_WORK_ROOT


def default_paths_root():
    candidate = packaged_data_dir("paths")
    return candidate if candidate.exists() else default_user_browse_root()


def default_maps_root():
    candidate = packaged_data_dir("maps")
    return candidate if candidate.exists() else default_user_browse_root()


def default_waypoint_tasks_root():
    candidate = packaged_data_dir("waypoint_tasks")
    return candidate if candidate.exists() else default_user_browse_root()


def default_waypoint_attrs_root():
    return packaged_or_source_path("task_execute_server", "waypoints_attributes")


def default_nav2_tree_nodes_xml():
    return packaged_or_source_path("nav2_behavior_tree", "nav2_tree_nodes.xml")


def default_task_editor_browse_root():
    candidate = packaged_data_dir("tasks")
    return candidate if candidate.exists() else default_user_browse_root()
